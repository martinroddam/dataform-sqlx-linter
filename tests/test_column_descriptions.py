import json
import os
from pathlib import Path

import pytest

from dataform_sqlx_linter.checks.column_descriptions import run as run_columns


@pytest.fixture
def write_graph(tmp_path: Path):
    """Create compiled_graph.json in a temp dir and chdir there."""
    old = os.getcwd()
    os.chdir(tmp_path)

    def _write(graph_dict):
        (tmp_path / "compiled_graph.json").write_text(
            json.dumps(graph_dict), encoding="utf-8"
        )

    yield _write
    os.chdir(old)


def test_skips_draft(write_graph, capsys):
    write_graph({
        "tables": [
            {
                "fileName": "definitions/draft_table.sqlx",
                "actionDescriptor": { "columns": [] },
                "bigquery": { "labels": { "lifecycle_stage": "draft" } },
            }
        ]
    })
    code = run_columns(["definitions/draft_table.sqlx"])
    out, err = capsys.readouterr()
    assert code == 0
    assert "Skipped definitions/draft_table.sqlx (lifecycle_stage is draft)" in out
    assert err == ""


def test_missing_columns_key(write_graph, capsys):
    write_graph({
        "tables": [
            {
                "fileName": "definitions/no_columns.sqlx",
                "actionDescriptor": {},
                "bigquery": { "labels": { "lifecycle_stage": "prod" } },
            }
        ]
    })
    code = run_columns(["definitions/no_columns.sqlx"])
    out, err = capsys.readouterr()
    assert code == 1
    assert "definitions/no_columns.sqlx is missing defined columns." in err
    assert "Some SQLX files are missing column descriptions." in err


def test_empty_columns_array(write_graph, capsys):
    write_graph({
        "tables": [
            {
                "fileName": "definitions/empty_columns.sqlx",
                "actionDescriptor": { "columns": [] },
                "bigquery": { "labels": { "lifecycle_stage": "prod" } },
            }
        ]
    })
    code = run_columns(["definitions/empty_columns.sqlx"])
    _, err = capsys.readouterr()
    assert code == 1
    assert "missing defined columns" in err


def test_column_missing_description(write_graph, capsys):
    write_graph({
        "tables": [
            {
                "fileName": "definitions/missing_descr.sqlx",
                "actionDescriptor": {
                    "columns": [
                        { "path": ["a"], "description": "ok" },
                        { "path": ["b", "c"], "description": "   " },  # empty
                        { "path": ["d"] }  # missing
                    ]
                },
                "bigquery": { "labels": { "lifecycle_stage": "prod" } },
            }
        ]
    })
    code = run_columns(["definitions/missing_descr.sqlx"])
    _, err = capsys.readouterr()
    assert code == 1
    assert 'Column "b.c" in definitions/missing_descr.sqlx is missing a description.' in err
    assert 'Column "d" in definitions/missing_descr.sqlx is missing a description.' in err


def test_unknown_path_when_not_list(write_graph, capsys):
    write_graph({
        "tables": [
            {
                "fileName": "definitions/unknown_path.sqlx",
                "actionDescriptor": {
                    "columns": [
                        { "path": "not-a-list", "description": "ok" },  # -> [unknown]
                        { "description": "also ok" },                    # -> [unknown]
                    ]
                },
                "bigquery": { "labels": { "lifecycle_stage": "prod" } },
            }
        ]
    })
    code = run_columns(["definitions/unknown_path.sqlx"])
    out, err = capsys.readouterr()
    assert code == 0
    assert "valid column descriptions" in out.lower()
    assert err == ""


def test_all_good(write_graph, capsys):
    write_graph({
        "tables": [
            {
                "fileName": "definitions/good.sqlx",
                "actionDescriptor": {
                    "columns": [
                        { "path": ["id"], "description": "Primary key" },
                        { "path": ["nested", "field"], "description": "Nested field" },
                    ]
                },
                "bigquery": { "labels": { "lifecycle_stage": "prod" } },
            }
        ]
    })
    code = run_columns(["definitions/good.sqlx"])
    out, err = capsys.readouterr()
    assert code == 0
    assert "valid column descriptions" in out.lower()
    assert err == ""


def test_only_checks_passed_files(write_graph, capsys):
    # Graph contains two tables; only one is passed into run(), so only that one is validated
    write_graph({
        "tables": [
            {
                "fileName": "definitions/checked.sqlx",
                "actionDescriptor": { "columns": [{ "path": ["x"], "description": "ok" }] },
                "bigquery": { "labels": { "lifecycle_stage": "prod" } },
            },
            {
                "fileName": "definitions/not_checked.sqlx",
                "actionDescriptor": { "columns": [] },  # would fail if checked
                "bigquery": { "labels": { "lifecycle_stage": "prod" } },
            }
        ]
    })
    code = run_columns(["definitions/checked.sqlx"])
    out, err = capsys.readouterr()
    assert code == 0
    assert err == ""

import json
import os
from pathlib import Path

import pytest

from dataform_sqlx_linter.checks.description import run as run_description


@pytest.fixture
def write_graph(tmp_path: Path):
    """Helper to create a compiled_graph.json file in a tmp_path and chdir there."""
    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    def _writer(graph_dict):
        (tmp_path / "compiled_graph.json").write_text(json.dumps(graph_dict), encoding="utf-8")
    yield _writer
    os.chdir(old_cwd)


def test_no_description(write_graph):
    """Fails if description element is missing entirely."""
    write_graph({
        "tables": [
            {
                "fileName": "definitions/missing.sqlx",
                "actionDescriptor": {},
                "bigquery": { "labels": { "lifecycle_stage": "prod" } }
            }
        ]
    })
    exit_code = run_description(["definitions/missing.sqlx"])
    assert exit_code == 1


def test_empty_description(write_graph):
    """Fails if description element is empty string."""
    write_graph({
        "tables": [
            {
                "fileName": "definitions/empty.sqlx",
                "actionDescriptor": { "description": "   " },
                "bigquery": { "labels": { "lifecycle_stage": "prod" } }
            }
        ]
    })
    exit_code = run_description(["definitions/empty.sqlx"])
    assert exit_code == 1


def test_valid_description(write_graph):
    """Passes if description is a non-empty string."""
    write_graph({
        "tables": [
            {
                "fileName": "definitions/ok.sqlx",
                "actionDescriptor": { "description": "My test table" },
                "bigquery": { "labels": { "lifecycle_stage": "prod" } }
            }
        ]
    })
    exit_code = run_description(["definitions/ok.sqlx"])
    assert exit_code == 0

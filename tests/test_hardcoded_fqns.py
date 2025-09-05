import json
import os
from pathlib import Path

import pytest

from dataform_sqlx_linter.checks.hardcoded_fqns import run as run_fqns


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


def test_no_actions_for_files_is_ok(write_graph, capsys):
    # Graph has an action, but we pass a different file name
    write_graph({
        "actions": [
            {
                "name": "a",
                "fileName": "definitions/a.sqlx",
                "target": {"schema": "ds", "name": "a"},
                "compiledQuery": "select 1"
            }
        ]
    })
    rc = run_fqns(["definitions/other.sqlx"])
    out, err = capsys.readouterr()
    assert rc == 0
    assert "nothing to check" in out.lower()


def test_ref_like_dependency_not_flagged(write_graph):
    # Action a depends on b; compiled query contains ds.b, which is accounted for
    write_graph({
        "actions": [
            {
                "name": "b",
                "fileName": "definitions/b.sqlx",
                "target": {"schema": "ds", "name": "b"},
                "compiledQuery": "select 1"
            },
            {
                "name": "a",
                "fileName": "definitions/a.sqlx",
                "dependencies": ["b"],
                "target": {"schema": "ds", "name": "a"},
                "compiledQuery": "select * from ds.b"
            }
        ]
    })
    rc = run_fqns(["definitions/a.sqlx"])
    assert rc == 0


def test_sources_are_accounted(write_graph):
    # Declared source listed in graph.sources is allowed without dependency
    write_graph({
        "actions": [
            {
                "name": "c",
                "fileName": "definitions/c.sqlx",
                "target": {"schema": "ds", "name": "c"},
                "compiledQuery": "select * from ext_ds.ext_table"
            }
        ],
        "sources": [
            {"target": {"schema": "ext_ds", "name": "ext_table"}}
        ]
    })
    rc = run_fqns(["definitions/c.sqlx"])
    assert rc == 0


def test_hardcoded_not_declared_flags(write_graph, capsys):
    # Action references an external table not covered by dependencies or sources
    write_graph({
        "actions": [
            {
                "name": "d",
                "fileName": "definitions/d.sqlx",
                "target": {"schema": "ds", "name": "d"},
                "compiledQuery": "select * from ext_ds.missing_dep"
            }
        ]
    })
    rc = run_fqns(["definitions/d.sqlx"])
    out, err = capsys.readouterr()
    assert rc == 1
    assert "suspected hard-coded table references" in err
    assert "ext_ds.missing_dep" in err


def test_information_schema_requires_declaration_fail(write_graph, capsys):
    write_graph({
        "actions": [
            {
                "name": "e",
                "fileName": "definitions/e.sqlx",
                "target": {"schema": "ds", "name": "e"},
                "compiledQuery": "select * from ds.INFORMATION_SCHEMA.COLUMNS"
            }
        ]
    })
    rc = run_fqns(["definitions/e.sqlx"])
    out, err = capsys.readouterr()
    assert rc == 1
    assert "suspected hard-coded table references" in err
    assert "ds.INFORMATION_SCHEMA.COLUMNS" in err


def test_information_schema_declared_source_ok(write_graph):
    write_graph({
        "actions": [
            {
                "name": "e",
                "fileName": "definitions/e.sqlx",
                "target": {"schema": "ds", "name": "e"},
                "compiledQuery": "select * from ds.INFORMATION_SCHEMA.COLUMNS"
            }
        ],
        "sources": [
            { "target": { "schema": "ds.INFORMATION_SCHEMA", "name": "COLUMNS" } }
        ]
    })
    rc = run_fqns(["definitions/e.sqlx"])
    assert rc == 0


def test_ignores_write_targets(write_graph):
    # CREATE TABLE ds.x AS SELECT * FROM ds.y  -> ds.x is write target, ds.y is read
    # ds.y not declared → should be flagged
    write_graph({
        "actions": [
            {
                "name": "f",
                "fileName": "definitions/f.sqlx",
                "target": {"schema": "ds", "name": "f"},
                "compiledQuery": "create table ds.x as select * from ds.y"
            }
        ]
    })
    # Still flags ds.y, since it's a read and not declared
    rc = run_fqns(["definitions/f.sqlx"])
    assert rc == 1

from __future__ import annotations
from pathlib import Path
from typing import Any

import sqlglot
from sqlglot import exp

from ..utils.io import (
    load_compiled_graph,
    GraphLoadError,
)
from ..utils.printing import PRINTER as p


def _display_name(file_path: str) -> str:
    """Return relative path if inside cwd, else basename."""
    pth = Path(file_path)
    try:
        rel = pth.resolve().relative_to(Path.cwd().resolve())
        return str(rel)
    except Exception:
        return pth.name


def _target_to_fqn(target: dict[str, Any] | None) -> str:
    """
    Dataform target -> canonical string.
    target = {"database": "proj", "schema": "ds", "name": "tbl"}
    Returns 'proj.ds.tbl' if database present, else 'ds.tbl'
    """
    if not target:
        return ""
    proj = str(target.get("database") or "").strip("`")
    ds = str(target.get("schema") or "").strip("`")
    tbl = str(target.get("name") or "").strip("`")
    if not (ds and tbl):
        return ""
    return f"{proj}.{ds}.{tbl}" if proj else f"{ds}.{tbl}"


def _normalize_bq_table(table_expr: exp.Table) -> str:
    """
    Convert a sqlglot Table node into 'project.dataset.table' or 'dataset.table'.
    """
    proj = (table_expr.catalog or "").strip("`")  # BigQuery: catalog == project
    ds = (table_expr.db or "").strip("`")        # BigQuery: db == dataset
    nm = (table_expr.name or "").strip("`")      # table name
    if not ds or not nm:
        return ""
    return f"{proj}.{ds}.{nm}" if proj else f"{ds}.{nm}"


def _collect_cte_names(tree: exp.Expression) -> set[str]:
    names: set[str] = set()
    for cte in tree.find_all(exp.CTE):
        alias = cte.alias
        if alias:
            names.add(alias)
    return names


def _is_write_target(table_expr: exp.Table) -> bool:
    """
    Return True only if this Table node is the actual write target of a CREATE/INSERT/COPY.
    For CTAS (CREATE TABLE t AS SELECT ... FROM s), skip only `t` (the target), not `s`.
    """
    create = table_expr.find_ancestor(exp.Create)
    if create is not None:
        # In sqlglot, the target of CREATE is `create.this`
        return create.this is table_expr

    insert = table_expr.find_ancestor(exp.Insert)
    if insert is not None:
        # In sqlglot, the target of INSERT is `insert.this`
        return insert.this is table_expr

    copy = table_expr.find_ancestor(exp.Copy)
    if copy is not None:
        # Target of COPY is `copy.this`
        return copy.this is table_expr

    return False



def _extract_read_tables(sql: str) -> set[str]:
    """
    Parse BigQuery SQL and return set of table identifiers used in read positions.
    Filters:
      - write targets (CREATE/INSERT/COPY)
      - CTE references
      - INFORMATION_SCHEMA
    """
    if not (sql and sql.strip()):
        return set()

    try:
        tree = sqlglot.parse_one(sql, read="bigquery")
    except Exception:
        # If parsing fails, be conservative and return empty (avoid false positives)
        return set()

    cte_names = _collect_cte_names(tree)
    results: set[str] = set()

    for t in tree.find_all(exp.Table):
        # Skip CTE references
        if (t.name or "") in cte_names:
            continue
        # Skip write targets
        if _is_write_target(t):
            continue
        fqn = _normalize_bq_table(t)
        if not fqn:
            continue
        results.add(fqn)

    return results


def _index_actions(
    graph: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], dict[str, str], set[str], dict[str, list[str]]]:
    """
    Build indices:
      - by_name: name -> action dict
      - name_to_fqn: name -> canonical FQN (for relations with a target)
      - source_fqns: set of declared sources' FQNs (if available)
      - by_file: fileName -> list of action names (to filter by file list)
    """
    actions: list[dict[str, Any]] = (
        graph.get("actions")  # some Dataform versions
        or graph.get("tables")  # others
        or []
    )

    by_name: dict[str, dict[str, Any]] = {}
    name_to_fqn: dict[str, str] = {}
    by_file: dict[str, list[str]] = {}

    for a in actions:
        name = a.get("name") or a.get("id")
        if not isinstance(name, str):
            continue
        by_name[name] = a

        # FQN for the action if it has a target
        fqn = _target_to_fqn(a.get("target") or a.get("canonicalTarget") or {})
        if fqn:
            name_to_fqn[name] = fqn

        # map by fileName so we can filter by changed files
        fn = a.get("fileName")
        if isinstance(fn, str):
            by_file.setdefault(fn, []).append(name)

    source_fqns: set[str] = set()
    for src in graph.get("sources", []):
        fqn = _target_to_fqn(src.get("target") or {})
        if fqn:
            source_fqns.add(fqn)

    return by_name, name_to_fqn, source_fqns, by_file


def _action_query(a: dict[str, Any]) -> str:
    # Prefer compiled SQL. Field names vary across Dataform versions.
    return (
        a.get("query")
        or a.get("compiledQuery")
        or a.get("sqlxCompiled")
        or ""
    )


def _action_dependencies(a: dict[str, Any]) -> list[str]:
    # Dataform exposes dependencies as action names (from ref() or config.dependencies)
    deps = a.get("dependencies")
    if isinstance(deps, list) and all(isinstance(x, str) for x in deps):
        return deps
    return []


def run(files: list[str]) -> int:
    """
    Return 1 if any action (within the provided files) appears to use hard-coded FQNs
    (i.e., referenced tables not covered by dependencies or declared sources). Else 0.
    """
    try:
        graph = load_compiled_graph()
    except GraphLoadError as e:
        p.error(str(e))
        return 1

    by_name, name_to_fqn, source_fqns, by_file = _index_actions(graph)

    # Build the set of action names to check based on files provided.
    to_check: set[str] = set()
    for f in files:
        if f in by_file:
            to_check.update(by_file[f])

    if not to_check:
        # Nothing to check (no actions found for given files)
        p.success("No actions found for provided files; nothing to check.")
        return 0

    has_errors = False

    for action_name in sorted(to_check):
        a = by_name.get(action_name, {})
        file_name = a.get("fileName") or action_name
        display = _display_name(file_name)

        sql = _action_query(a)
        parsed_tables = _extract_read_tables(sql)

        deps = set(_action_dependencies(a))
        dep_fqns = {name_to_fqn[d] for d in deps if d in name_to_fqn}
        accounted = set(dep_fqns) | source_fqns

        suspects = {t for t in parsed_tables if t not in accounted}

        if suspects:
            has_errors = True
            p.error(
                f"{display}: suspected hard-coded table references "
                f"(use ref()): {', '.join(sorted(suspects))}"
            )

    if has_errors:
        p.footer_fail("Some SQLX files use fully-qualified tables instead of ref().")
        return 1

    p.footer_ok("No likely hard-coded FQNs found.")
    return 0

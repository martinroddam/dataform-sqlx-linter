from __future__ import annotations
from typing import List, Any

from ..utils.io import (
    load_compiled_graph,
    iter_tables_for_files,
    get_lifecycle_stage,
    GraphLoadError,
)
from ..utils.printing import PRINTER as p


def _path_to_str(path: Any) -> str:
    if isinstance(path, list) and all(isinstance(x, str) for x in path):
        return ".".join(path)
    return "[unknown]"


def run(files: List[str]) -> int:
    try:
        graph = load_compiled_graph()
    except GraphLoadError as e:
        p.error(str(e))
        return 1

    has_errors = False

    for table in iter_tables_for_files(graph, files):
        file_name = table.get("fileName")
        lifecycle = get_lifecycle_stage(table)

        if lifecycle == "draft":
            p.skip(f"Skipped {file_name} (lifecycle_stage is draft)")
            continue

        columns = (table.get("actionDescriptor") or {}).get("columns")
        if not isinstance(columns, list) or not columns:
            p.error(f"{file_name} is missing defined columns.")
            has_errors = True
            continue

        for col in columns:
            desc = col.get("description")
            if not isinstance(desc, str) or desc.strip() == "":
                col_path = _path_to_str(col.get("path"))
                p.error(f"Column \"{col_path}\" in {file_name} is missing a description.")
                has_errors = True

    if has_errors:
        p.footer_fail("Some SQLX files are missing column descriptions.")
        return 1

    p.footer_ok("All SQLX files have valid column descriptions.")
    return 0

from __future__ import annotations
from typing import List
from ..utils.io import load_compiled_graph, iter_tables_for_files, get_lifecycle_stage, GraphLoadError
from ..utils.printing import PRINTER as p


def run(files: List[str]) -> int:
    try:
        graph = load_compiled_graph()
    except GraphLoadError as e:
        p.error(str(e))
        return 1

    has_errors = False

    for table in iter_tables_for_files(graph, files):
        file_name = table.get("fileName")
        description = (table.get("actionDescriptor") or {}).get("description")
        lifecycle = get_lifecycle_stage(table)

        if not isinstance(description, str) or description.strip() == "":
            if lifecycle != "draft":
                p.error(f"Missing description in {file_name}")
                has_errors = True
            else:
                p.skip(f"Skipped {file_name} (lifecycle_stage is draft)")

    if has_errors:
        p.footer_fail("Some SQLX files are missing required descriptions.")
        return 1

    p.footer_ok("All SQLX files have valid descriptions.")
    return 0

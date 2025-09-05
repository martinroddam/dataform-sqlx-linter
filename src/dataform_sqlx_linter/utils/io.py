from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List


DEFAULT_GRAPH_PATH = "compiled_graph.json"


class GraphLoadError(RuntimeError):
    pass


def load_compiled_graph(path: str | Path = DEFAULT_GRAPH_PATH) -> Dict:
    """
    Load compiled_graph.json and return a dict.
    Raises GraphLoadError with a friendly message on failure.
    """
    p = Path(path)
    try:
        text = p.read_text(encoding="utf-8")
    except FileNotFoundError as e:
        raise GraphLoadError(f"Could not find {p}") from e
    except OSError as e:
        raise GraphLoadError(f"Failed reading {p}: {e}") from e

    try:
        graph = json.loads(text)
    except json.JSONDecodeError as e:
        raise GraphLoadError(f"Failed to parse {p}: {e}") from e

    if not isinstance(graph, dict):
        raise GraphLoadError(f"Unexpected structure in {p}: expected JSON object at top level")
    return graph


def normalize_changed_files(files: Iterable[str]) -> List[str]:
    """
    Trim, dedupe, and preserve order. (GitHub passes comma-joined lists.)
    """
    seen = set()
    out: List[str] = []
    for raw in files:
        if not raw:
            continue
        for part in str(raw).split(","):
            f = part.strip()
            if f and f not in seen:
                seen.add(f)
                out.append(f)
    return out


def iter_tables_for_files(graph: Dict, files: Iterable[str]) -> Iterator[Dict]:
    """
    Yield tables from graph.tables whose fileName is in `files`.
    """
    targets = set(files)
    for tbl in (graph.get("tables") or []):
        fn = tbl.get("fileName")
        if fn and fn in targets:
            yield tbl


def get_lifecycle_stage(table: dict[str, Any]) -> str | None:
    bigquery = table.get("bigquery") or {}
    if not isinstance(bigquery, dict):
        return None
    labels = bigquery.get("labels") or {}
    if not isinstance(labels, dict):
        return None
    ls = labels.get("lifecycle_stage")
    return ls if isinstance(ls, str) else None

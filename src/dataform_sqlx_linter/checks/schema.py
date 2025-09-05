from __future__ import annotations
import re
from pathlib import Path
from typing import List, Optional

from ..utils.printing import PRINTER as p

SCHEMA_RE = re.compile(r'\bschema\s*:\s*(["\'])(?P<val>[^"\']+)\1')
TYPE_RE = re.compile(r'\btype\s*:\s*(["\']?)(?P<val>[a-zA-Z_]+)\1')
VALID_TYPES = {"view", "table", "incremental"}


def _extract_config_block(content: str) -> Optional[str]:
    start = content.find("config {")
    if start == -1:
        return None

    brace_count = 0
    start_idx = -1
    end_idx = -1

    for i in range(start, len(content)):
        ch = content[i]
        if ch == "{":
            brace_count += 1
            if start_idx == -1:
                start_idx = i
        elif ch == "}":
            brace_count -= 1
            if brace_count == 0:
                end_idx = i
                break

    if start_idx == -1 or end_idx == -1:
        return None

    return content[start_idx + 1 : end_idx].strip()


def _strip_js_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)       # /* ... */
    text = re.sub(r"//.*?$", "", text, flags=re.MULTILINE)       # // ...
    return text


def _display_name(file_path: str) -> str:
    """Return relative path if inside cwd, else basename."""
    pth = Path(file_path)
    try:
        rel = pth.resolve().relative_to(Path.cwd().resolve())
        return str(rel)
    except Exception:
        return pth.name


def run(files: List[str]) -> int:
    has_errors = False

    for file_path in files:
        path = Path(file_path)
        display = _display_name(file_path)

        try:
            content = path.read_text(encoding="utf-8")
        except Exception as e:
            p.error(f"{display}: Failed to read file. {e}")
            has_errors = True
            continue

        cfg = _extract_config_block(content)
        if not cfg:
            p.error(f"{display}: Missing or malformed config block.")
            has_errors = True
            continue

        cfg = _strip_js_comments(cfg)

        # Type gate
        m_type = TYPE_RE.search(cfg)
        if m_type:
            tval = m_type.group("val").lower()
            if tval not in VALID_TYPES:
                p.skip(f"Skipped {display} (type is '{tval}')")
                continue

        # Enforce explicit quoted schema
        m_schema = SCHEMA_RE.search(cfg)
        if not m_schema or not m_schema.group("val").strip():
            p.error(f"{display}: Schema must be explicitly set.")
            has_errors = True

    if has_errors:
        p.footer_fail("Some SQLX files are missing explicit schema.")
        return 1

    p.footer_ok("All relevant SQLX files have an explicit schema set.")
    return 0

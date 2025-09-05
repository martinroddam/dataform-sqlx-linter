from __future__ import annotations
import argparse
import json
import os
import sys
from typing import Any, Callable, Optional, TypedDict

from .checks.column_descriptions import run as check_columns
from .checks.description import run as check_description
from .checks.schema import run as check_schema
from .checks.hardcoded_fqns import run as check_hardcoded_fqns


class Config(TypedDict, total=False):
    include: list[str]
    exclude: list[str]
    fail_fast: bool


CHECKS: dict[str, Callable[[list[str]], int]] = {
    "description": check_description,
    "schema": check_schema,
    "columns": check_columns,
    "hardcoded_fqns": check_hardcoded_fqns,
}


def _split_csv(s: Optional[str]) -> list[str]:
    return [x.strip() for x in s.split(",")] if s else []


def _load_config(path: Optional[str]) -> Config:
    if not path:
        return {}

    try:
        loaded: Any = {}  # declare once to avoid "no-redef"
        if path.lower().endswith((".yml", ".yaml")):
            import yaml  # optional dependency (install pyyaml + types-PyYAML for mypy)
            with open(path, "r", encoding="utf-8") as f:
                loaded = yaml.safe_load(f) or {}
        else:
            with open(path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
    except FileNotFoundError:
        print(f"⚠️  Config not found: {path}", file=sys.stderr)
        return {}
    except Exception as e:
        print(f"⚠️  Failed to load config {path}: {e}", file=sys.stderr)
        return {}

    # Normalize into our Config type
    cfg: Config = {}
    if isinstance(loaded, dict):
        inc = loaded.get("include")
        if isinstance(inc, list) and all(isinstance(x, str) for x in inc):
            cfg["include"] = list(inc)

        exc = loaded.get("exclude")
        if isinstance(exc, list) and all(isinstance(x, str) for x in exc):
            cfg["exclude"] = list(exc)

        ff = loaded.get("fail_fast")
        if isinstance(ff, bool):
            cfg["fail_fast"] = ff

    return cfg


def cli(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run Dataform SQLX checks.")
    parser.add_argument("--config", help="YAML/JSON with include/exclude/fail_fast")
    parser.add_argument("--include", help="CSV of checks to run")
    parser.add_argument("--exclude", help="CSV of checks to skip")
    parser.add_argument("--fail-fast", action="store_true", help="Stop on first failing check")
    parser.add_argument("files", nargs="+", help="Changed .sqlx files to check")
    args = parser.parse_args(argv)

    file_cfg = _load_config(args.config)
    include = _split_csv(args.include) or _split_csv(os.getenv("CHECKS_INCLUDE")) or file_cfg.get("include", [])
    exclude = _split_csv(args.exclude) or _split_csv(os.getenv("CHECKS_EXCLUDE")) or file_cfg.get("exclude", [])
    fail_fast = bool(args.fail_fast or (os.getenv("CHECKS_FAIL_FAST") == "1") or file_cfg.get("fail_fast", False))

    # resolve checks
    selected = set(CHECKS)
    if include:
        unknown = [c for c in include if c not in CHECKS]
        for c in unknown:
            print(f"⚠️  Unknown check in include: {c}", file=sys.stderr)
        selected = {c for c in include if c in CHECKS}
    if exclude:
        unknown = [c for c in exclude if c not in CHECKS]
        for c in unknown:
            print(f"⚠️  Unknown check in exclude: {c}", file=sys.stderr)
        selected -= {c for c in exclude if c in CHECKS}

    if not selected:
        print("ℹ️  No checks selected.", file=sys.stderr)
        return 0

    print(f"🔎 Running checks: {', '.join(sorted(selected))}")
    any_fail = False
    for name in sorted(selected):
        print(f"\n——— {name.upper()} ———")
        rc = CHECKS[name](args.files)
        if rc != 0:
            any_fail = True
            if fail_fast:
                print("⛔ fail-fast: stopping.", file=sys.stderr)
                break

    if any_fail:
        return 1
    print("\n✅ All selected checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(cli())

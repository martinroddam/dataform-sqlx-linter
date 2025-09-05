from __future__ import annotations
import os
import sys
from dataclasses import dataclass

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[31m"
YELLOW = "\033[33m"
GREEN = "\033[32m"
CYAN = "\033[36m"


def _supports_color() -> bool:
    if os.getenv("NO_COLOR"):
        return False
    if os.getenv("FORCE_COLOR"):
        return True
    return sys.stdout.isatty() or sys.stderr.isatty()


@dataclass
class Printer:
    color: bool = _supports_color()

    def _c(self, code: str, text: str) -> str:
        if not self.color:
            return text
        return f"{code}{text}{RESET}"

    # Sections / headers
    def header(self, title: str) -> None:
        print(self._c(CYAN + BOLD, f"\n——— {title} ———"))

    # Informational
    def info(self, msg: str) -> None:
        print(msg)

    def success(self, msg: str) -> None:
        print(self._c(GREEN, f"✅ {msg}"))

    def skip(self, msg: str) -> None:
        print(self._c(CYAN, f"✅ {msg}"))

    # Problems
    def warn(self, msg: str) -> None:
        print(self._c(YELLOW, f"⚠️  {msg}"), file=sys.stderr)

    def error(self, msg: str) -> None:
        print(self._c(RED, f"❌ {msg}"), file=sys.stderr)

    # Footers
    def footer_ok(self, msg: str = "All selected checks passed.") -> None:
        self.success(msg)

    def footer_fail(self, msg: str) -> None:
        self.error(msg)


# A convenient default instance to import
PRINTER = Printer()

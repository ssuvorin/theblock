#!/usr/bin/env python3

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path
from typing import Iterator, NamedTuple

FILE_LIMIT = 700
CLASS_LIMIT = 300
FUNCTION_LIMIT = 80
ROOT = Path(__file__).resolve().parents[1]
SOURCE_SUFFIXES = {".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}
EXCLUDED_PARTS = {
    ".git",
    ".next",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
}
CLASS_PATTERN = re.compile(r"\bclass\s+([A-Za-z_$][\w$]*)[^;{}]*\{")
FUNCTION_PATTERNS = (
    re.compile(r"\b(?:async\s+)?function\s*([A-Za-z_$][\w$]*)?\s*\([^;{}]*\)[^;{}]*\{"),
    re.compile(r"(?:async\s+)?(?:\([^;{}]*\)|[A-Za-z_$][\w$]*)\s*(?::\s*[^=;{}]+)?=>\s*\{"),
    re.compile(
        r"(?m)^\s*(?:(?:public|private|protected|static|async|readonly)\s+)*"
        r"(?:get\s+|set\s+)?([A-Za-z_$][\w$]*)\s*\([^;{}]*\)"
        r"\s*(?::\s*[^{=]+)?\{"
    ),
)
CONTROL_NAMES = {"if", "for", "switch", "while", "catch", "with"}


class Violation(NamedTuple):
    path: Path
    line: int
    unit: str
    actual: int
    limit: int


def is_excluded(relative: Path) -> bool:
    if relative.parts and relative.parts[0] == "mockups":
        return True
    # Alembic revisions are emitted by --autogenerate; splitting them would break the tool.
    if relative.parent.match("**/migrations/versions"):
        return True
    return any(part in EXCLUDED_PARTS or part == "_generated" for part in relative.parts)


def source_files() -> Iterator[Path]:
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in SOURCE_SUFFIXES:
            continue
        if not is_excluded(path.relative_to(ROOT)):
            yield path


def line_count(text: str) -> int:
    return len(text.splitlines())


def python_units(path: Path, text: str) -> Iterator[Violation]:
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError:
        return
    for node in ast.walk(tree):
        end = getattr(node, "end_lineno", None)
        if end is None:
            continue
        if isinstance(node, ast.ClassDef):
            start = min((item.lineno for item in node.decorator_list), default=node.lineno)
            size = end - start + 1
            if size > CLASS_LIMIT:
                yield Violation(path, start, f"class {node.name}", size, CLASS_LIMIT)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            start = min((item.lineno for item in node.decorator_list), default=node.lineno)
            size = end - start + 1
            if size > FUNCTION_LIMIT:
                yield Violation(path, start, f"function {node.name}", size, FUNCTION_LIMIT)


def mask_non_code(text: str) -> str:
    chars = list(text)
    index = 0
    state = "code"
    quote = ""
    while index < len(chars):
        char = chars[index]
        following = chars[index + 1] if index + 1 < len(chars) else ""
        if state == "code" and char == "/" and following in {"/", "*"}:
            state = "line" if following == "/" else "block"
            chars[index] = chars[index + 1] = " "
            index += 2
            continue
        if state == "code" and char in {"'", '"', "`"}:
            state, quote, chars[index] = "string", char, " "
        elif state == "line":
            if char == "\n":
                state = "code"
            else:
                chars[index] = " "
        elif state == "block":
            if char == "*" and following == "/":
                chars[index] = chars[index + 1] = " "
                state = "code"
                index += 2
                continue
            if char != "\n":
                chars[index] = " "
        elif state == "string":
            if char == "\\":
                chars[index] = " "
                if index + 1 < len(chars) and chars[index + 1] != "\n":
                    chars[index + 1] = " "
                    index += 2
                    continue
            elif char == quote:
                state, chars[index] = "code", " "
            elif char != "\n":
                chars[index] = " "
        index += 1
    return "".join(chars)


def block_size(text: str, opening: int) -> int | None:
    depth = 0
    for index in range(opening, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                start_line = text.count("\n", 0, opening) + 1
                end_line = text.count("\n", 0, index) + 1
                return end_line - start_line + 1
    return None


def typescript_units(path: Path, text: str) -> Iterator[Violation]:
    code = mask_non_code(text)
    for match in CLASS_PATTERN.finditer(code):
        size = block_size(code, match.end() - 1)
        if size is not None and size > CLASS_LIMIT:
            line = code.count("\n", 0, match.start()) + 1
            yield Violation(path, line, f"class {match.group(1)}", size, CLASS_LIMIT)
    seen: set[int] = set()
    for pattern in FUNCTION_PATTERNS:
        for match in pattern.finditer(code):
            opening = match.end() - 1
            name = match.group(1) if match.lastindex else None
            if opening in seen or name in CONTROL_NAMES:
                continue
            seen.add(opening)
            size = block_size(code, opening)
            if size is not None and size > FUNCTION_LIMIT:
                line = code.count("\n", 0, match.start()) + 1
                yield Violation(path, line, f"function {name or '<anonymous>'}", size, FUNCTION_LIMIT)


def check_file(path: Path) -> Iterator[Violation]:
    text = path.read_text(encoding="utf-8", errors="replace")
    size = line_count(text)
    if size > FILE_LIMIT:
        yield Violation(path, 1, "file", size, FILE_LIMIT)
    if path.suffix == ".py":
        yield from python_units(path, text)
    else:
        yield from typescript_units(path, text)


def main() -> int:
    violations = [item for path in source_files() for item in check_file(path)]
    for item in sorted(violations):
        relative = item.path.relative_to(ROOT)
        print(f"{relative}:{item.line}: {item.unit} is {item.actual} lines (max {item.limit})")
    if violations:
        print(f"size guard failed with {len(violations)} violation(s)", file=sys.stderr)
        return 1
    print("size guard passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

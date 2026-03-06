from __future__ import annotations

import ast
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
TASK_MODULES = (
    BACKEND_ROOT / "core" / "tasks.py",
    BACKEND_ROOT / "analytics" / "tasks.py",
    BACKEND_ROOT / "integrations" / "tasks.py",
)


def _retry_with_backoff_call_lines(module_path: Path) -> list[int]:
    module_ast = ast.parse(module_path.read_text(encoding="utf-8"))
    lines: list[int] = []
    for node in ast.walk(module_ast):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute) or func.attr != "retry_with_backoff":
            continue
        has_reason_keyword = any(keyword.arg == "reason" for keyword in node.keywords)
        if not has_reason_keyword:
            lines.append(node.lineno)
    return lines


def test_retry_with_backoff_calls_explicitly_set_reason_keyword():
    missing: list[str] = []
    for module_path in TASK_MODULES:
        for line_number in _retry_with_backoff_call_lines(module_path):
            missing.append(f"{module_path}:{line_number}")
    assert not missing, "retry_with_backoff calls missing reason keyword: " + ", ".join(missing)

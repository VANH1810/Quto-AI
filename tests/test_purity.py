from __future__ import annotations

import ast
import json
from pathlib import Path

from risk_engine import CommuneState, evaluate
from risk_engine.schemas import assessment_to_dict

from test_validate import CFG, make_input

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "backend" / "risk_engine"
BANNED_IMPORTS = {"requests", "httpx", "psycopg", "sqlalchemy"}


def test_risk_engine_imports_no_network_or_database_clients() -> None:
    for path, tree in _package_trees():
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = {alias.name.split(".")[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = {node.module.split(".")[0]}
            else:
                continue
            assert not (
                names & BANNED_IMPORTS
            ), f"{path} imports {names & BANNED_IMPORTS}"


def test_risk_engine_never_reads_wall_clock() -> None:
    for path, tree in _package_trees():
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(
                node.func, ast.Attribute
            ):
                continue
            attr = node.func.attr
            owner = node.func.value
            datetime_now = (
                attr == "now" and isinstance(owner, ast.Name) and owner.id == "datetime"
            )
            time_time = (
                attr == "time" and isinstance(owner, ast.Name) and owner.id == "time"
            )
            assert not datetime_now, f"{path} calls datetime.now"
            assert not time_time, f"{path} calls time.time"


def test_evaluate_replay_returns_byte_identical_output() -> None:
    payload = make_input()
    outputs, state = evaluate(payload, CFG, CommuneState(commune_code="03136"))
    replay, _ = evaluate(payload, CFG, state)
    assert _stable(outputs) == _stable(replay)


def _package_trees() -> list[tuple[Path, ast.AST]]:
    return [
        (path, ast.parse(path.read_text(encoding="utf-8")))
        for path in sorted(PACKAGE.glob("*.py"))
    ]


def _stable(outputs: list[object]) -> bytes:
    text = json.dumps(
        [assessment_to_dict(item) for item in outputs],
        sort_keys=True,
        separators=(",", ":"),
    )
    return text.encode("utf-8")

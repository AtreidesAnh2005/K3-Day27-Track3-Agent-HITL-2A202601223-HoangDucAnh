"""Audit schema and append-only JSON audit log helpers."""
from __future__ import annotations

import json
import os

from typing import Optional

from pydantic import BaseModel

AUDIT_LOG_PATH = os.path.join(os.path.dirname(__file__), "audit_log.json")


class AuditEntry(BaseModel):
    timestamp: str
    agent_id: str
    action: str
    confidence: float
    reviewer_id: str
    decision: str
    # Optional extras (beyond the required 6 fields in Readme_1.md section 5.3)
    # so the edited value and execution outcome are traceable per
    # exercise.md Phase 6 ("edited arguments", "execution status").
    action_value: Optional[float] = None
    status: Optional[str] = None


def read_audit_log(path: str | None = None) -> list[dict]:
    """Read all existing audit entries. Returns [] if the file is missing/empty."""
    target_path = path if path is not None else AUDIT_LOG_PATH
    if not os.path.exists(target_path):
        return []
    with open(target_path, "r", encoding="utf-8") as f:
        content = f.read().strip()
        if not content:
            return []
        return json.loads(content)


def append_audit_entry(entry: AuditEntry, path: str | None = None) -> None:
    """Append a single AuditEntry without overwriting existing history."""
    target_path = path if path is not None else AUDIT_LOG_PATH
    entries = read_audit_log(target_path)
    entries.append(entry.model_dump())
    with open(target_path, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)

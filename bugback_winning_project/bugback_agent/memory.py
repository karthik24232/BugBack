from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime

class PersistentMemory:
    def __init__(self, path: str = "data/memory.json"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("[]", encoding="utf-8")

    def load(self) -> List[Dict[str, Any]]:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return []

    def search(self, area: str, issue_type: str) -> List[Dict[str, Any]]:
        records = self.load()
        matches = []
        for r in records:
            same_area = r.get("affected_area") == area
            same_issue = issue_type.lower() in r.get("issue_type", "").lower() or r.get("issue_type", "").lower() in issue_type.lower()
            if same_area or same_issue:
                matches.append(r)
        return matches[-10:]

    def save_result(self, result: Dict[str, Any]) -> None:
        records = self.load()
        compact = {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "complaint": result.get("complaint"),
            "status": result.get("status"),
            "severity": result.get("severity"),
            "affected_area": result.get("plan", {}).get("affected_area"),
            "issue_type": result.get("plan", {}).get("issue_type"),
            "likely_cause": result.get("likely_cause"),
        }
        records.append(compact)
        self.path.write_text(json.dumps(records[-100:], indent=2), encoding="utf-8")

    def clear(self) -> None:
        self.path.write_text("[]", encoding="utf-8")

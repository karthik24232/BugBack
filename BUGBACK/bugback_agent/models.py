from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, List, Optional, Any


@dataclass
class AgentStep:
    step: int
    title: str
    detail: str
    status: str = "done"
    tool: Optional[str] = None
    evidence: Optional[str] = None


@dataclass
class ComplaintPlan:
    complaint: str
    issue_type: str
    affected_area: str
    reproduction_tool: str
    expected_behavior: str
    suspected_behavior: str
    test_data: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0


@dataclass
class BrowserEvidence:
    verified: bool
    bug_type: str
    steps: List[str]
    observations: List[str]
    screenshot_path: Optional[str] = None


@dataclass
class EvidenceBundle:
    browser: BrowserEvidence
    matching_logs: List[Dict[str, Any]]
    matching_flags: List[Dict[str, Any]]
    memory_matches: List[Dict[str, Any]]


@dataclass
class PolicyDecision:
    recommended_action: str
    requires_human_approval: bool
    reason: str
    allowed_autonomous_actions: List[str]
    blocked_autonomous_actions: List[str]


@dataclass
class FinalInvestigation:
    created_at: str
    complaint: str
    status: str
    severity: str
    plan: ComplaintPlan
    evidence: EvidenceBundle
    likely_cause: str
    root_cause_reasoning: str
    policy: PolicyDecision
    engineering_ticket: str
    customer_response: str
    timeline: List[AgentStep]

    def to_dict(self):
        return asdict(self)

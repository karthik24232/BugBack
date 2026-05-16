from __future__ import annotations
import json
import os
from datetime import datetime
from typing import Dict, List, Any
from dotenv import load_dotenv
from openai import OpenAI
from .models import AgentStep, ComplaintPlan, EvidenceBundle, FinalInvestigation, PolicyDecision
from .tools import BrowserReproductionTool, DataTools
from .memory import PersistentMemory

load_dotenv()

MODEL = "nvidia/nemotron-3-super-120b-a12b"


class BugBackAgent:
    def __init__(self, base_url="http://127.0.0.1:5001", memory_path="data/memory.json"):
        self.browser = BrowserReproductionTool(base_url=base_url)
        self.data = DataTools()
        self.memory = PersistentMemory(memory_path)
        self.timeline: List[AgentStep] = []
        self.llm = OpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=os.environ["NVIDIA_API_KEY"],
        )

    def add_step(self, title: str, detail: str, tool: str | None = None, evidence: str | None = None):
        self.timeline.append(AgentStep(len(self.timeline) + 1, title, detail, "done", tool, evidence))

    def plan_complaint(self, complaint: str) -> ComplaintPlan:
        self.add_step("Read customer complaint", complaint, tool="complaint_intake")

        prompt = f"""You are a support triage agent. Classify this customer complaint and respond with JSON only — no markdown, no explanation.

Complaint: {complaint}

Return exactly this JSON structure:
{{
  "issue_type": "one-line description of the bug",
  "affected_area": "checkout" or "payments" or "frontend" or "general",
  "reproduction_tool": "browser.discount_checkout_test" or "browser.duplicate_charge_test" or "browser.cart_freeze_test" or "manual_triage_required",
  "expected_behavior": "what the product should do",
  "suspected_behavior": "what seems to be going wrong",
  "test_data": {{}},
  "confidence": a number between 0.0 and 1.0
}}

Classification rules:
- Discount, promo code, coupon, SAVE20 → affected_area "checkout", reproduction_tool "browser.discount_checkout_test", add test_data {{"discount_code": "SAVE20"}}
- Charged twice, double charge, duplicate payment → affected_area "payments", reproduction_tool "browser.duplicate_charge_test"
- Page freeze, cart drawer stuck, UI hang → affected_area "frontend", reproduction_tool "browser.cart_freeze_test"
- Anything else → affected_area "general", reproduction_tool "manual_triage_required"
"""

        response = self.llm.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.choices[0].message.content.strip()

        # Strip markdown code fences if the model wraps its output
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        data = json.loads(raw)
        plan = ComplaintPlan(
            complaint=complaint,
            issue_type=data["issue_type"],
            affected_area=data["affected_area"],
            reproduction_tool=data["reproduction_tool"],
            expected_behavior=data["expected_behavior"],
            suspected_behavior=data["suspected_behavior"],
            test_data=data.get("test_data", {}),
            confidence=float(data.get("confidence", 0.7)),
        )

        self.add_step(
            "Created investigation plan",
            f"Classified as {plan.issue_type}; selected {plan.reproduction_tool}; affected area={plan.affected_area}.",
            tool="nemotron_planner",
            evidence=f"confidence={round(plan.confidence * 100)}%",
        )
        return plan

    def collect_evidence(self, plan: ComplaintPlan) -> EvidenceBundle:
        self.add_step("Selected browser tool", f"Using {plan.reproduction_tool} to reproduce the customer issue.", tool="tool_router")
        browser_result = self.browser.run(plan)
        self.add_step(
            "Ran browser reproduction",
            "Browser automation completed against the local demo store.",
            tool=plan.reproduction_tool,
            evidence="verified=True" if browser_result.verified else "verified=False",
        )

        logs = self.data.search_logs(plan.affected_area)
        self.add_step("Searched system logs", f"Found {len(logs)} matching logs for area '{plan.affected_area}'.", tool="log_search")

        flags = self.data.search_flags(plan.affected_area)
        self.add_step("Checked feature flags", f"Found {len(flags)} enabled flags/releases for area '{plan.affected_area}'.", tool="feature_flag_lookup")

        memory_matches = self.memory.search(plan.affected_area, plan.issue_type)
        self.add_step("Checked persistent memory", f"Found {len(memory_matches)} similar prior investigations.", tool="persistent_memory")

        return EvidenceBundle(browser=browser_result, matching_logs=logs, matching_flags=flags, memory_matches=memory_matches)

    def choose_likely_cause(self, plan: ComplaintPlan, evidence: EvidenceBundle) -> tuple[str, str]:
        logs_text = "\n".join([f"- [{l['level']}] {l['message']} (flag={l.get('feature_flag')})" for l in evidence.matching_logs]) or "None"
        flags_text = "\n".join([f"- {f['name']} | risk={f['risk']} | owner={f['owner']} | released={f['released_at']}" for f in evidence.matching_flags]) or "None"
        obs_text = "\n".join([f"- {o}" for o in evidence.browser.observations]) or "None"

        prompt = f"""You are a senior engineer doing root cause analysis. Given the evidence below, identify the most likely root cause of this bug and explain your reasoning.

Issue: {plan.issue_type}
Affected area: {plan.affected_area}
Browser verified: {evidence.browser.verified}

Browser observations:
{obs_text}

System logs:
{logs_text}

Enabled feature flags / recent releases:
{flags_text}

Respond with JSON only — no markdown, no explanation outside the JSON:
{{
  "cause": "the name of the most likely feature flag or release, or \\"Unknown\\" if unclear",
  "reasoning": "2-3 sentence explanation of why this is the likely cause, referencing specific log entries or flags"
}}
"""
        response = self.llm.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        data = json.loads(raw)
        cause = data.get("cause", "Unknown")
        reasoning = data.get("reasoning", "No reasoning provided.")

        step_title = "Identified likely root cause" if cause != "Unknown" else "Could not identify root cause"
        self.add_step(step_title, reasoning, tool="nemotron_root_cause", evidence=cause if cause != "Unknown" else None)
        return cause, reasoning

    def determine_severity(self, plan: ComplaintPlan, evidence: EvidenceBundle) -> str:
        similar_count = len(evidence.memory_matches)
        verified = evidence.browser.verified
        if plan.affected_area == "payments" and verified:
            severity = "P0"
        elif similar_count >= 3 and verified:
            severity = "P1"
        elif plan.affected_area == "checkout" and verified:
            severity = "P1" if similar_count >= 1 else "P2"
        elif verified:
            severity = "P2"
        else:
            severity = "P3"
        self.add_step("Assigned severity", f"Severity set to {severity}. Similar memory matches={similar_count}; verified={verified}.", tool="severity_policy")
        return severity

    def apply_policy(self, plan: ComplaintPlan, cause: str, severity: str) -> PolicyDecision:
        action = "Create engineering ticket and notify support."
        if cause != "Unknown":
            action = f"Recommend temporarily disabling `{cause}` after human approval; create ticket immediately."

        risky = plan.affected_area in {"checkout", "payments"} or severity in {"P0", "P1"}
        policy = PolicyDecision(
            recommended_action=action,
            requires_human_approval=risky,
            reason=(
                "Rollback/refund/payment actions affect revenue or customer money, so the agent must ask for approval."
                if risky else
                "Low-risk frontend issue: agent can create the ticket and customer reply without approval."
            ),
            allowed_autonomous_actions=[
                "create_engineering_ticket",
                "draft_customer_response",
                "save_investigation_memory",
                "notify_support_queue",
            ],
            blocked_autonomous_actions=[
                "disable_feature_flag_without_approval",
                "issue_refund_without_approval",
                "email_customer_without_review",
            ],
        )
        self.add_step("Applied safety policy", policy.reason, tool="policy_guardrail", evidence="approval_required=" + str(policy.requires_human_approval))
        return policy

    def write_ticket(self, plan: ComplaintPlan, evidence: EvidenceBundle, cause: str, reasoning: str, severity: str, policy: PolicyDecision) -> str:
        steps = "\n".join([f"{i+1}. {s}" for i, s in enumerate(evidence.browser.steps)])
        observations = "\n".join([f"- {o}" for o in evidence.browser.observations])
        logs = "\n".join([f"- {l['timestamp']} [{l['level']}] {l['message']} (flag={l.get('feature_flag')})" for l in evidence.matching_logs]) or "- No matching logs found."
        flags = "\n".join([f"- {f['name']} | risk={f['risk']} | owner={f['owner']} | released={f['released_at']}" for f in evidence.matching_flags]) or "- No matching enabled flags found."
        memory = "\n".join([f"- {m.get('created_at')}: {m.get('issue_type')} caused by {m.get('likely_cause')} severity={m.get('severity')}" for m in evidence.memory_matches]) or "- No similar prior investigations."

        prompt = f"""You are a senior engineer writing an internal bug report. Write a clear, structured engineering ticket in markdown.

Use exactly these sections in order:
# BugBack Engineering Ticket
(header block with Severity, Status, Issue, Affected Area, Likely Cause, Human Approval Required)

## Summary
(2-3 sentence narrative explaining what is broken and why it matters)

## Customer Complaint
(quote the complaint)

## Reproduction Steps
(the browser steps)

## Evidence
(observations, logs, feature flags)

## Root Cause Analysis
(explain the reasoning in plain English)

## Prior Incidents
(memory matches or "No prior incidents.")

## Recommended Action
(what should be done, and whether human approval is required)

## Screenshot
(path or "No screenshot generated.")

---

Here is the raw data to use:

Severity: {severity}
Status: {"VERIFIED" if evidence.browser.verified else "UNVERIFIED"}
Issue: {plan.issue_type}
Affected area: {plan.affected_area}
Likely cause: {cause}
Human approval required: {policy.requires_human_approval}

Customer complaint: {plan.complaint}

Expected behavior: {plan.expected_behavior}
Suspected behavior: {plan.suspected_behavior}

Browser steps:
{steps}

Browser observations:
{observations}

Matching logs:
{logs}

Matching feature flags:
{flags}

Prior investigations:
{memory}

Root cause reasoning: {reasoning}

Recommended action: {policy.recommended_action}
Policy reason: {policy.reason}

Screenshot: {evidence.browser.screenshot_path or "No screenshot generated."}
"""
        response = self.llm.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content.strip()

    def write_customer_response(self, plan: ComplaintPlan, evidence: EvidenceBundle) -> str:
        verified_str = "confirmed and reproduced by our team" if evidence.browser.verified else "not yet fully reproduced"
        prompt = f"""You are a empathetic customer support agent. Write a short, professional email response to this customer complaint.

Complaint: {plan.complaint}
Issue type: {plan.issue_type}
Affected area: {plan.affected_area}
Bug verified by automated testing: {evidence.browser.verified}
Status: {verified_str}

Guidelines:
- Start with "Hi," and end with "Best,\\nCustomer Support Team"
- Be warm and apologetic but concise (3-4 sentences max)
- If verified, tell them we confirmed the issue and engineering is on it
- If not verified, ask for more details (screenshot, order number, device)
- Do not mention internal terms like feature flags, severity, or root cause
- Do not use placeholders like [NAME] or [ORDER]
"""
        response = self.llm.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content.strip()

    def investigate(self, complaint: str) -> FinalInvestigation:
        self.timeline = []
        plan = self.plan_complaint(complaint)
        evidence = self.collect_evidence(plan)
        cause, reasoning = self.choose_likely_cause(plan, evidence)
        severity = self.determine_severity(plan, evidence)
        policy = self.apply_policy(plan, cause, severity)
        ticket = self.write_ticket(plan, evidence, cause, reasoning, severity, policy)
        response = self.write_customer_response(plan, evidence)
        self.add_step("Generated outputs", "Created engineering ticket, support response, and investigation record.", tool="report_writer")

        result = FinalInvestigation(
            created_at=datetime.now().isoformat(timespec="seconds"),
            complaint=complaint,
            status="VERIFIED" if evidence.browser.verified else "NEEDS_TRIAGE",
            severity=severity,
            plan=plan,
            evidence=evidence,
            likely_cause=cause,
            root_cause_reasoning=reasoning,
            policy=policy,
            engineering_ticket=ticket,
            customer_response=response,
            timeline=self.timeline,
        )
        self.memory.save_result(result.to_dict())
        self.add_step("Saved persistent memory", "Investigation saved so future complaints can be prioritized using history.", tool="persistent_memory")
        result.timeline = self.timeline
        return result

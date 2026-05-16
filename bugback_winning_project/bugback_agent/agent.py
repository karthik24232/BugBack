from __future__ import annotations
from datetime import datetime
from typing import Dict, List, Any
from .models import AgentStep, ComplaintPlan, EvidenceBundle, FinalInvestigation, PolicyDecision
from .tools import BrowserReproductionTool, DataTools
from .memory import PersistentMemory


class BugBackAgent:
    """
    Hackathon-ready autonomous workflow agent.

    In the actual NVIDIA hackathon, this class is the logic you connect to OpenClaw.
    Nemotron should replace or augment plan_complaint(), root-cause reasoning, and writing.
    The browser/log/flag/memory/policy functions are real tools the agent calls.
    """
    def __init__(self, base_url="http://127.0.0.1:5001", memory_path="data/memory.json"):
        self.browser = BrowserReproductionTool(base_url=base_url)
        self.data = DataTools()
        self.memory = PersistentMemory(memory_path)
        self.timeline: List[AgentStep] = []

    def add_step(self, title: str, detail: str, tool: str | None = None, evidence: str | None = None):
        self.timeline.append(AgentStep(len(self.timeline) + 1, title, detail, "done", tool, evidence))

    def plan_complaint(self, complaint: str) -> ComplaintPlan:
        text = complaint.lower()
        self.add_step("Read customer complaint", complaint, tool="complaint_intake")

        if any(k in text for k in ["discount", "promo", "coupon", "save20"]):
            plan = ComplaintPlan(
                complaint=complaint,
                issue_type="Discount disappears during checkout",
                affected_area="checkout",
                reproduction_tool="browser.discount_checkout_test",
                expected_behavior="SAVE20 should stay applied from cart through checkout and keep total at $80.",
                suspected_behavior="Discount is applied in cart but removed after checkout route loads.",
                test_data={"discount_code": "SAVE20"},
                confidence=0.94,
            )
        elif any(k in text for k in ["charged twice", "double charged", "two charges", "charged me twice"]):
            plan = ComplaintPlan(
                complaint=complaint,
                issue_type="Duplicate payment authorization",
                affected_area="payments",
                reproduction_tool="browser.duplicate_charge_test",
                expected_behavior="One payment click should create exactly one authorization.",
                suspected_behavior="Payment retry handler creates two successful authorizations.",
                test_data={},
                confidence=0.91,
            )
        elif any(k in text for k in ["freeze", "froze", "stuck", "cart drawer", "page froze"]):
            plan = ComplaintPlan(
                complaint=complaint,
                issue_type="Frontend cart freeze",
                affected_area="frontend",
                reproduction_tool="browser.cart_freeze_test",
                expected_behavior="Cart drawer should open and page should stay responsive.",
                suspected_behavior="Opening the cart drawer causes an infinite loading/freeze state.",
                test_data={},
                confidence=0.86,
            )
        else:
            plan = ComplaintPlan(
                complaint=complaint,
                issue_type="Unknown customer-reported issue",
                affected_area="general",
                reproduction_tool="manual_triage_required",
                expected_behavior="Product should complete the customer flow without errors.",
                suspected_behavior="Customer reports an issue but the affected area is unclear.",
                test_data={},
                confidence=0.45,
            )

        self.add_step(
            "Created investigation plan",
            f"Classified as {plan.issue_type}; selected {plan.reproduction_tool}; affected area={plan.affected_area}.",
            tool="nemotron_planner_stub",
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
        if evidence.matching_logs:
            log_flags = [log.get("feature_flag") for log in evidence.matching_logs if log.get("feature_flag")]
            for flag in evidence.matching_flags:
                if flag.get("name") in log_flags:
                    cause = flag["name"]
                    reasoning = (
                        f"Browser reproduction verified the customer-visible failure. Logs in {plan.affected_area} "
                        f"reference {cause}, and the enabled feature flag belongs to the same product area."
                    )
                    self.add_step("Identified likely root cause", reasoning, tool="root_cause_ranker", evidence=cause)
                    return cause, reasoning

        if evidence.matching_flags:
            cause = evidence.matching_flags[0]["name"]
            reasoning = f"No direct log match was found, but {cause} is the most recent enabled flag in the affected area."
            self.add_step("Identified possible root cause", reasoning, tool="root_cause_ranker", evidence=cause)
            return cause, reasoning

        self.add_step("Could not identify root cause", "No matching feature flag or log evidence found.", tool="root_cause_ranker")
        return "Unknown", "The agent could not confidently connect the issue to a release or feature flag."

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

        return f"""# BugBack Engineering Ticket

**Severity:** {severity}  
**Status:** {'VERIFIED' if evidence.browser.verified else 'UNVERIFIED'}  
**Issue:** {plan.issue_type}  
**Affected Area:** {plan.affected_area}  
**Likely Cause:** `{cause}`  
**Human Approval Required:** {policy.requires_human_approval}

## Customer Complaint
> {plan.complaint}

## Expected Behavior
{plan.expected_behavior}

## Observed/Suspected Behavior
{plan.suspected_behavior}

## Browser Reproduction Steps
{steps}

## Browser Observations
{observations}

## Matching Logs
{logs}

## Matching Feature Flags / Releases
{flags}

## Persistent Memory Matches
{memory}

## Root Cause Reasoning
{reasoning}

## Recommended Action
{policy.recommended_action}

## Safety Policy
{policy.reason}

## Screenshot
{evidence.browser.screenshot_path or 'No screenshot generated.'}
"""

    def write_customer_response(self, plan: ComplaintPlan, evidence: EvidenceBundle) -> str:
        if evidence.browser.verified:
            return f"""Hi,

Thank you for reporting this. We investigated the issue and confirmed that there is a problem affecting the {plan.affected_area} flow.

Our team has reproduced the problem and escalated it to engineering with the exact steps and supporting system evidence. We are working on the safest fix and will follow up once it is resolved.

We’re sorry for the inconvenience and appreciate you flagging this.

Best,  
Customer Support Team
"""
        return f"""Hi,

Thank you for reporting this. We reviewed your message and started an investigation, but we could not fully reproduce the issue yet.

We have shared the report with our technical team. If you can send a screenshot, browser/device details, or order number, that would help us investigate faster.

Best,  
Customer Support Team
"""

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

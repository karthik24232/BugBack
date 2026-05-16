"""
BugBack Edge — OpenClaw / Nemotron adapter

The core agent (bugback_agent/agent.py) uses NVIDIA Nemotron via build.nvidia.com for:
  - Complaint classification       (plan_complaint)
  - Root cause reasoning           (choose_likely_cause)
  - Engineering ticket writing     (write_ticket)
  - Customer response writing      (write_customer_response)

This file exposes run_bugback_task() as the entry point for OpenClaw to call.
"""

from bugback_agent import BugBackAgent


def run_bugback_task(complaint: str, store_url: str = "http://127.0.0.1:5001") -> dict:
    """
    Takes a raw customer complaint and runs a full autonomous investigation.

    Tools the agent runs autonomously:
      - browser reproduction (Playwright)
      - system log search
      - feature flag lookup
      - persistent memory read/write
      - safety policy enforcement

    Requires human approval before:
      - feature flag rollback
      - refund issuance
      - outbound customer email
    """
    agent = BugBackAgent(base_url=store_url, memory_path="data/memory.json")
    result = agent.investigate(complaint)
    return result.to_dict()

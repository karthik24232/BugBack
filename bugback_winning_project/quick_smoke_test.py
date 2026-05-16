"""
Optional smoke test.

Run this only after starting the fake store in another terminal:
python demo_store/app.py

Then:
python quick_smoke_test.py
"""
from bugback_agent import BugBackAgent

complaints = [
    "I tried to use my discount code SAVE20, but it disappeared at checkout.",
    "The app charged me twice for the same order after I clicked pay once.",
    "The page froze when I opened the cart drawer.",
]

agent = BugBackAgent(base_url="http://127.0.0.1:5001")
for complaint in complaints:
    result = agent.investigate(complaint)
    print("=" * 80)
    print("Complaint:", complaint)
    print("Status:", result.status)
    print("Severity:", result.severity)
    print("Likely cause:", result.likely_cause)
    print("Approval required:", result.policy.requires_human_approval)

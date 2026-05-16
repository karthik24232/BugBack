import json
from pathlib import Path
import streamlit as st
import pandas as pd
from bugback_agent import BugBackAgent
from bugback_agent.memory import PersistentMemory

st.set_page_config(page_title="BugBack Edge", page_icon="🐞", layout="wide")

st.title("🐞 BugBack Edge")
st.caption("Autonomous customer complaint → verified bug → evidence → safe engineering action")

st.info(
    "Edge Mode: customer complaints, browser sessions, logs, feature flags, and memory stay local. "
    "The OpenClaw/Nemotron adapter files show where to wire in the hackathon SDK."
)

with st.sidebar:
    st.header("Demo controls")
    base_url = st.text_input("Demo store URL", "http://127.0.0.1:5001")
    st.write("Start the store first:")
    st.code("python demo_store/app.py")
    if st.button("Clear persistent memory"):
        PersistentMemory("data/memory.json").clear()
        st.success("Memory cleared.")

samples = {
    "Discount disappears": "I tried to use my discount code SAVE20, but it disappeared at checkout.",
    "Double charge": "The app charged me twice for the same order after I clicked pay once.",
    "Page freeze": "The page froze when I opened the cart drawer.",
}

col_a, col_b = st.columns([2, 1])
with col_a:
    selected = st.selectbox("Sample complaint", list(samples.keys()))
    complaint = st.text_area("Customer complaint", samples[selected], height=110)
with col_b:
    st.subheader("What judges should notice")
    st.write("✅ Real browser reproduction")
    st.write("✅ Multi-step agent timeline")
    st.write("✅ Persistent memory changes severity")
    st.write("✅ Safety policy blocks risky actions")
    st.write("✅ Local/edge privacy framing")

run = st.button("Run autonomous investigation", type="primary")

if run:
    try:
        agent = BugBackAgent(base_url=base_url, memory_path="data/memory.json")
        result = agent.investigate(complaint)
    except Exception as e:
        st.error("Investigation failed. Make sure the fake demo store is running in another terminal.")
        st.exception(e)
        st.stop()

    st.success("Investigation complete")

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Status", result.status)
    m2.metric("Severity", result.severity)
    m3.metric("Affected Area", result.plan.affected_area)
    m4.metric("Likely Cause", result.likely_cause)
    m5.metric("Approval Required", "Yes" if result.policy.requires_human_approval else "No")

    st.divider()

    st.header("Agent timeline")
    timeline_rows = [
        {
            "Step": s.step,
            "Action": s.title,
            "Tool": s.tool or "—",
            "Evidence": s.evidence or "—",
            "Detail": s.detail,
        }
        for s in result.timeline
    ]
    st.dataframe(pd.DataFrame(timeline_rows), use_container_width=True, hide_index=True)

    st.divider()

    left, right = st.columns([1.1, 0.9])
    with left:
        st.header("Browser evidence")
        st.write(f"**Verified:** {result.evidence.browser.verified}")
        for obs in result.evidence.browser.observations:
            st.code(obs)
        if result.evidence.browser.screenshot_path and Path(result.evidence.browser.screenshot_path).exists():
            st.image(result.evidence.browser.screenshot_path, caption="Browser reproduction screenshot")

    with right:
        st.header("Safety policy")
        st.warning(result.policy.reason if result.policy.requires_human_approval else result.policy.reason)
        st.write("**Recommended action:**")
        st.info(result.policy.recommended_action)
        st.write("**Allowed autonomous actions**")
        for a in result.policy.allowed_autonomous_actions:
            st.write(f"- {a}")
        st.write("**Blocked without approval**")
        for a in result.policy.blocked_autonomous_actions:
            st.write(f"- {a}")

        approve_col, reject_col = st.columns(2)
        with approve_col:
            if st.button("Simulate approval"):
                st.success("Approval recorded. In a real integration, this would call the feature-flag API.")
        with reject_col:
            if st.button("Create ticket only"):
                st.info("Safe fallback selected: ticket created, no rollback executed.")

    st.divider()

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Engineering ticket",
        "Customer response",
        "Logs",
        "Feature flags",
        "Memory"
    ])

    with tab1:
        st.markdown(result.engineering_ticket)
        st.download_button("Download engineering ticket", result.engineering_ticket, "bugback_ticket.md", "text/markdown")

    with tab2:
        st.markdown(result.customer_response)
        st.download_button("Download customer response", result.customer_response, "customer_response.txt", "text/plain")

    with tab3:
        st.json(result.evidence.matching_logs)

    with tab4:
        st.json(result.evidence.matching_flags)

    with tab5:
        memory_records = PersistentMemory("data/memory.json").load()
        st.write("Persistent memory saved locally in `data/memory.json`.")
        st.json(memory_records)

else:
    st.write("Run an investigation to see the autonomous workflow.")
    st.markdown("""
### Winning demo order
1. Start the fake store.
2. Run this dashboard.
3. Test all three sample complaints.
4. Run the discount complaint twice to show memory affects severity.
5. Point out the safety policy: the agent can recommend rollback, but cannot execute risky actions without approval.
""")

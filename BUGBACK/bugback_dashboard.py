import json
from pathlib import Path
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from bugback_agent import BugBackAgent
from bugback_agent.memory import PersistentMemory


def render_evidence_graph(evidence, cause, reasoning):
    obs_items  = "".join(f'<div class="item">{o}</div>' for o in evidence.browser.observations)
    log_items  = "".join(f'<div class="item">[{l["level"]}] {l["message"]}</div>' for l in evidence.matching_logs) or '<div class="item muted">No matching logs</div>'
    flag_items = "".join(f'<div class="item">{f["name"]} · risk={f["risk"]}</div>' for f in evidence.matching_flags) or '<div class="item muted">No matching flags</div>'

    return f"""
    <style>
      @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@400;500;600&display=swap');
      .eg-wrap {{
        display: grid;
        grid-template-columns: 1fr 120px 1fr;
        align-items: center;
        gap: 0;
        background: #0f1117;
        border: 1px solid #1e2230;
        border-radius: 12px;
        padding: 28px 20px;
        font-family: 'IBM Plex Sans', sans-serif;
        position: relative;
      }}
      .eg-inputs {{ display: flex; flex-direction: column; gap: 12px; }}
      .eg-card {{
        background: #151820;
        border: 1px solid #1e2230;
        border-radius: 8px;
        padding: 12px 14px;
      }}
      .eg-card-title {{
        font-size: 9px; letter-spacing: .14em; text-transform: uppercase;
        color: #4a5068; margin-bottom: 8px; font-weight: 600;
      }}
      .item {{
        font-family: 'IBM Plex Mono', monospace;
        font-size: 10px; color: #9ba3c2; line-height: 1.6;
        border-left: 2px solid #1e2230; padding-left: 8px; margin-bottom: 4px;
      }}
      .item:last-child {{ margin-bottom: 0; }}
      .muted {{ color: #4a5068; }}
      .eg-center {{
        display: flex; flex-direction: column; align-items: center;
        justify-content: center; gap: 10px; position: relative;
      }}
      .nemotron-node {{
        background: #00e5b015;
        border: 1px solid #00e5b0;
        border-radius: 50%;
        width: 72px; height: 72px;
        display: flex; flex-direction: column;
        align-items: center; justify-content: center;
        font-size: 8px; letter-spacing: .12em; text-transform: uppercase;
        color: #00e5b0; font-weight: 600; text-align: center;
        line-height: 1.4;
        box-shadow: 0 0 24px #00e5b030;
        animation: glow 2.4s ease-in-out infinite;
      }}
      @keyframes glow {{
        0%,100% {{ box-shadow: 0 0 24px #00e5b030; }}
        50%      {{ box-shadow: 0 0 40px #00e5b055; }}
      }}
      .arrow-label {{ font-size: 9px; color: #4a5068; letter-spacing: .08em; text-transform: uppercase; }}
      .eg-output {{}}
      .cause-card {{
        background: #151820;
        border: 1px solid #00e5b0;
        border-radius: 8px;
        padding: 14px 16px;
        margin-bottom: 12px;
      }}
      .cause-label {{
        font-size: 9px; letter-spacing: .14em; text-transform: uppercase;
        color: #00e5b0; margin-bottom: 6px; font-weight: 600;
      }}
      .cause-name {{
        font-family: 'IBM Plex Mono', monospace;
        font-size: 14px; color: #dde1ec; font-weight: 600;
      }}
      .reasoning-card {{
        background: #151820;
        border: 1px solid #1e2230;
        border-left: 3px solid #00e5b0;
        border-radius: 0 8px 8px 0;
        padding: 12px 14px;
      }}
      .reasoning-label {{
        font-size: 9px; letter-spacing: .14em; text-transform: uppercase;
        color: #4a5068; margin-bottom: 8px; font-weight: 600;
      }}
      .reasoning-text {{ font-size: 11px; color: #9ba3c2; line-height: 1.7; }}
      svg.connectors {{ position: absolute; inset: 0; pointer-events: none; overflow: visible; }}
    </style>
    <div class="eg-wrap">
      <div class="eg-inputs">
        <div class="eg-card">
          <div class="eg-card-title">Browser observations</div>
          {obs_items}
        </div>
        <div class="eg-card">
          <div class="eg-card-title">System logs</div>
          {log_items}
        </div>
        <div class="eg-card">
          <div class="eg-card-title">Feature flags</div>
          {flag_items}
        </div>
      </div>

      <div class="eg-center">
        <div class="arrow-label">input</div>
        <div class="nemotron-node">NVIDIA<br>Nemotron</div>
        <div class="arrow-label">output</div>
      </div>

      <div class="eg-output">
        <div class="cause-card">
          <div class="cause-label">Root cause identified</div>
          <div class="cause-name">{cause}</div>
        </div>
        <div class="reasoning-card">
          <div class="reasoning-label">Model reasoning</div>
          <div class="reasoning-text">{reasoning}</div>
        </div>
      </div>
    </div>
    """

st.set_page_config(page_title="BugBack Edge", page_icon="🐞", layout="wide")

st.title("🐞 BugBack Edge")
st.caption("Autonomous customer complaint → verified bug → evidence → safe engineering action")

with st.sidebar:
    base_url = st.text_input("Demo store URL", "http://127.0.0.1:5001")
    if st.button("Clear persistent memory"):
        PersistentMemory("data/memory.json").clear()
        st.success("Memory cleared.")

samples = {
    "Discount disappears": "I tried to use my discount code SAVE20, but it disappeared at checkout.",
    "Double charge": "The app charged me twice for the same order after I clicked pay once.",
    "Page freeze": "The page froze when I opened the cart drawer.",
}

selected = st.selectbox("Sample complaint", list(samples.keys()))
complaint = st.text_area("Customer complaint", samples[selected], height=110)

run = st.button("Run autonomous investigation", type="primary")

if run:
    try:
        with st.status("Running autonomous investigation...", expanded=True) as status:
            def on_step(step):
                tool_tag = f" &nbsp;`{step.tool}`" if step.tool else ""
                evidence_tag = f" &nbsp;· {step.evidence}" if step.evidence else ""
                status.write(f"**{step.step}.** {step.title}{tool_tag}{evidence_tag}")

            agent = BugBackAgent(base_url=base_url, memory_path="data/memory.json", on_step=on_step)
            result = agent.investigate(complaint)
            status.update(label="Investigation complete", state="complete", expanded=False)
    except Exception as e:
        st.error("Investigation failed. Make sure the fake demo store is running in another terminal.")
        st.exception(e)
        st.stop()

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

    st.header("Evidence graph · what Nemotron reasoned over")
    components.html(
        render_evidence_graph(result.evidence, result.likely_cause, result.root_cause_reasoning),
        height=360,
    )

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
    st.write("Select a complaint above and click Run autonomous investigation.")

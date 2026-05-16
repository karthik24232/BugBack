# BugBack Edge

**BugBack Edge** is a local autonomous support-to-engineering agent that turns vague customer complaints into verified bug reports, root-cause evidence, safe engineering recommendations, and customer-ready responses.

It is designed for the NVIDIA Hack-a-Claw style requirement:

- autonomous agent workflow
- live tool use
- persistent memory
- multi-step reasoning
- local/edge privacy framing
- safety policy guardrails
- OpenClaw/Nemotron integration points

## What makes this version stronger

This is not just a hard-coded chatbot. It includes:

1. A fake ecommerce site with **three real intentional bugs**.
2. A Playwright browser agent that actually reproduces the bugs.
3. Mock live system logs and feature flags.
4. Persistent memory saved in `data/memory.json`.
5. Severity escalation based on prior memory.
6. Safety policy that blocks risky actions without approval.
7. Generated engineering ticket and customer response.
8. Adapter files for OpenClaw/Nemotron/NemoClaw integration.

## Run it

Unzip the folder, then:

```bash
cd bugback_winning_project
pip install -r requirements.txt
playwright install chromium
```

Start the broken demo store in Terminal 1:

```bash
python demo_store/app.py
```

Start BugBack Edge in Terminal 2:

```bash
streamlit run bugback_dashboard.py
```

Open the Streamlit URL, usually:

```text
http://localhost:8501
```

The fake store runs at:

```text
http://127.0.0.1:5001
```

## Best demo complaints

### 1. Discount bug

```text
I tried to use my discount code SAVE20, but it disappeared at checkout.
```

Expected result:

- Bug verified by browser automation
- Affected area: checkout
- Likely cause: `promo-engine-v2`
- Policy: human approval required before rollback

### 2. Double charge bug

```text
The app charged me twice for the same order after I clicked pay once.
```

Expected result:

- Bug verified by browser automation
- Affected area: payments
- Likely cause: `payment-retry-handler`
- Severity: P0
- Policy blocks refunds/payment actions without approval

### 3. Page freeze bug

```text
The page froze when I opened the cart drawer.
```

Expected result:

- Bug verified by browser automation
- Affected area: frontend
- Likely cause: `cart-drawer-v3`

## How to show persistent memory

Run the discount bug twice.

The second run should show memory matches in the dashboard and can raise the priority because the agent remembers similar prior investigations.

## Judge pitch

> BugBack Edge is a local autonomous agent that helps companies go from vague customer complaint to verified engineering evidence. If a customer says “my discount disappeared,” BugBack opens the website, reproduces the issue in a browser, checks logs and feature flags, identifies the likely broken release, generates an engineering ticket, drafts a customer response, and applies safety rules so risky actions like rollbacks or refunds require human approval.

## OpenClaw / Nemotron integration

The core agent is in:

```text
bugback_agent/agent.py
```

The OpenClaw adapter sketch is in:

```text
opencLaw_nemoclaw/opencLaw_adapter_example.py
```

The security policy concept is in:

```text
opencLaw_nemoclaw/bugback_policy.yaml
```

When the event provides the SDK, connect `BugBackAgent.investigate()` to OpenClaw as a tool/task handler, and use Nemotron for planning, reasoning, and writing.
# BugBack
